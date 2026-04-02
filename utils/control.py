import datetime
import traceback

from CTFd.utils import get_config
from .db import DBContainer, db
from .docker import DockerUtils
from .routers import Router


class ControlUtil:
    @staticmethod
    def try_add_container(user_id, challenge_id):
        if DBContainer.get_all_alive_container_count() > get_config("whale:max_containers", 1000):
            # TODO: total container count may exceed configured limit if many users create container at the same time
            # this may happen especially when event is just started
            # simple solution is to lock this two lines, but implementing a queue system is better
            # historically this was intensional so players gets a better experience when event is just started, but better fix it still
            return False, 'Max container count exceed.'
        container = DBContainer.create_container_record(user_id, challenge_id)
        try:
            DockerUtils.add_container(container)
            ok, msg = Router.register(container)
            if ok:
                return True, 'Container created'
        except Exception:
            print(traceback.format_exc())
            msg = 'Container creation failed'
        try:
            DockerUtils.remove_container(container)
        except Exception:
            pass
        DBContainer.remove_container_record(user_id)
        return False, msg

    @staticmethod
    def try_remove_container(user_id):
        container = DBContainer.get_current_containers(user_id=user_id)
        if not container:
            return False, 'No such container'
        for _ in range(3):  # configurable? as "onerror_retry_cnt"
            try:
                ok, msg = Router.unregister(container)
                if not ok:
                    return False, msg
                DockerUtils.remove_container(container)
                DBContainer.remove_container_record(user_id)
                return True, 'Container destroyed'
            except Exception:
                print(traceback.format_exc())
        return False, 'Failed when destroying instance, please contact admin!'

    @staticmethod
    def try_renew_container(user_id):
        container = DBContainer.get_current_containers(user_id)
        if not container:
            return False, 'No such container'
        timeout = int(get_config("whale:docker_timeout", "3600"))
        container.start_time = container.start_time + \
                               datetime.timedelta(seconds=timeout)
        if container.start_time > datetime.datetime.now():
            container.start_time = datetime.datetime.now()
            # race condition? useless maybe?
            # useful when docker_timeout < poll timeout (10 seconds)
            # doesn't make any sense
        else:
            return False, 'Invalid container'
        container.renew_count += 1
        db.session.commit()
        return True, 'Container Renewed'

from CTFd.utils import get_config

from .base import BaseRouter
from .frp import FrpRouter

_routers = {
    cls.name: cls
    for cls in BaseRouter.__subclasses__()
}


def instanciate(cls):
    return cls()


@instanciate
class Router:
    _name = ''
    _router = None

    def __getattr__(self, name: str):
        router_conftype = get_config("whale:router_type", "frp")
        if Router._name != router_conftype:
            Router._router = _routers[router_conftype]()
            Router._name = router_conftype
        return getattr(Router._router, name)

    def reset(self):
        Router._name = ''
        Router._router = None


__all__ = ["Router"]

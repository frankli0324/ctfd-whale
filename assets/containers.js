const $ = CTFd.lib.$;

function htmlentities(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function copyToClipboard(event, str) {
    // Select element
    const el = document.createElement('textarea');
    el.value = str;
    el.setAttribute('readonly', '');
    el.style.position = 'absolute';
    el.style.left = '-9999px';
    document.body.appendChild(el);
    el.select();
    document.execCommand('copy');
    document.body.removeChild(el);

    $(event.target).tooltip({
        title: "Copied!",
        trigger: "manual"
    });
    $(event.target).tooltip("show");

    setTimeout(function () {
        $(event.target).tooltip("hide");
    }, 1500);
}

$(".click-copy").click(function (e) {
    copyToClipboard(e, $(this).data("copy"));
})

async function delete_container(user_id, challenge_id) {
    let response = await CTFd.fetch("/api/v1/plugins/ctfd-whale/admin/container?user_id=" + user_id + "&challenge_id=" + challenge_id, {
        method: "DELETE",
        credentials: "same-origin",
        headers: {
            Accept: "application/json",
            "Content-Type": "application/json"
        }
    });
    response = await response.json();
    return response.success;
}
async function renew_container(user_id, challenge_id) {
    let response = await CTFd.fetch(
        "/api/v1/plugins/ctfd-whale/admin/container?user_id=" + user_id + "&challenge_id=" + challenge_id, {
        method: "PATCH",
        credentials: "same-origin",
        headers: {
            Accept: "application/json",
            "Content-Type": "application/json"
        }
    });
    response = await response.json();
    return response.success;
}

$('#containers-renew-button').click(function (e) {
    let containers = $("input[data-user-id]:checked").map(function () {
        return [[$(this).data("user-id"), $(this).data("challenge-id")]];
    });
    CTFd.ui.ezq.ezQuery({
        title: "Renew Containers",
        body: `Are you sure you want to renew the selected ${containers.length} container(s)?`,
        success: async function () {
            await Promise.all(containers.toArray().map((container) => renew_container(container[0],container[1])));
            location.reload();
        }
    });
});

$('#containers-delete-button').click(function (e) {
    let containers = $("input[data-user-id]:checked").map(function () {
        return [[$(this).data("user-id"), $(this).data("challenge-id")]];
    });
    CTFd.ui.ezq.ezQuery({
        title: "Delete Containers",
        body: `Are you sure you want to delete the selected ${containers.length} container(s)?`,
        success: async function () {
            await Promise.all(containers.toArray().map((container) => delete_container(container[0],container[1])));
            location.reload();
        }
    });
});

$(".delete-container").click(function (e) {
    e.preventDefault();
    let container_id = $(this).attr("container-id");
    let user_id = $(this).attr("user-id");
    let challenge_id = $(this).attr("challenge-id");
    CTFd.ui.ezq.ezQuery({
        title: "Destroy Container",
        body: "<span>Are you sure you want to delete <strong>Container #{0}</strong>?</span>".format(
            htmlentities(container_id)
        ),
        success: async function () {
            await delete_container(user_id, challenge_id);
            location.reload();
        }
    });
});

$(".renew-container").click(function (e) {
    e.preventDefault();
    let container_id = $(this).attr("container-id");
    let user_id = $(this).attr("user-id");
    let challenge_id = $(this).attr("challenge-id");
    CTFd.ui.ezq.ezQuery({
        title: "Renew Container",
        body: "<span>Are you sure you want to renew <strong>Container #{0}</strong>?</span>".format(
            htmlentities(container_id)
        ),
        success: async function () {
            await renew_container(user_id, challenge_id);
            location.reload();
        },
    });
});
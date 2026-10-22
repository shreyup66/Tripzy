(function () {
  const { api, h, renderList, showLoadError, action, bindForm, toast } = window.Tripzy;
  const results = document.getElementById("search-results");
  const incoming = document.getElementById("incoming-list");
  const outgoing = document.getElementById("outgoing-list");
  const friends = document.getElementById("friend-list");
  let lastQuery = "";

  function person(u) {
    return h("div", { class: "grow" }, h("div", { class: "title" }, u.display_name), h("div", { class: "sub" }, u.email));
  }

  function refreshAll() {
    loadIncoming();
    loadOutgoing();
    loadFriends();
    if (lastQuery) search(lastQuery);
  }

  async function search(q) {
    lastQuery = q;
    const users = await api(`/api/users/search?q=${encodeURIComponent(q)}`);
    renderList(results, users, (u) => {
      let control;
      if (u.relationship === "friend") control = h("span", { class: "badge badge-owner" }, "Friend");
      else if (u.relationship === "outgoing") control = h("span", { class: "badge" }, "Request sent");
      else if (u.relationship === "incoming")
        control = h("button", { class: "btn btn-small btn-primary", type: "button", onclick: (e) =>
          action(e.currentTarget, async () => { await api(`/api/friend-requests/${u.request_id}/accept`, { method: "POST" }); refreshAll(); }, { success: `You and ${u.display_name} are now friends` }) }, "Accept request");
      else
        control = h("button", { class: "btn btn-small btn-primary", type: "button", onclick: (e) =>
          action(e.currentTarget, async () => {
            const r = await api("/api/friend-requests", { method: "POST", body: { recipient_id: u.id } });
            toast(r.status === "accepted" ? `You and ${u.display_name} are now friends` : `Friend request sent to ${u.display_name}`);
            refreshAll();
          }) }, "Add friend");
      return h("li", {}, person(u), control);
    }, "No matching users.");
  }

  bindForm(document.getElementById("search-form"), async (values) => {
    const q = (values.q || "").trim();
    if (q.length < 2) {
      toast("Type at least 2 characters to search.", "error");
      return;
    }
    await search(q);
  });

  async function loadIncoming() {
    try {
      const list = await api("/api/friend-requests?direction=incoming");
      renderList(incoming, list, (r) => h("li", {}, person(r.requester),
        h("div", { class: "actions" },
          h("button", { class: "btn btn-small btn-primary", type: "button", onclick: (e) =>
            action(e.currentTarget, async () => { await api(`/api/friend-requests/${r.id}/accept`, { method: "POST" }); refreshAll(); }, { success: "Friend request accepted" }) }, "Accept"),
          h("button", { class: "btn btn-small", type: "button", onclick: (e) =>
            action(e.currentTarget, async () => { await api(`/api/friend-requests/${r.id}/reject`, { method: "POST" }); refreshAll(); }, { success: "Request rejected" }) }, "Reject"))),
        "No incoming requests.");
    } catch (err) { showLoadError(incoming, err); }
  }

  async function loadOutgoing() {
    try {
      const list = await api("/api/friend-requests?direction=outgoing");
      renderList(outgoing, list, (r) => h("li", {}, person(r.recipient),
        h("button", { class: "btn btn-small", type: "button", onclick: (e) =>
          action(e.currentTarget, async () => { await api(`/api/friend-requests/${r.id}`, { method: "DELETE" }); refreshAll(); },
            { confirm: `Cancel your friend request to ${r.recipient.display_name}?`, success: "Request cancelled" }) }, "Cancel")),
        "No pending sent requests.");
    } catch (err) { showLoadError(outgoing, err); }
  }

  async function loadFriends() {
    try {
      const list = await api("/api/friends");
      renderList(friends, list, (f) => h("li", {}, person(f),
        h("button", { class: "btn btn-small", type: "button", onclick: (e) =>
          action(e.currentTarget, async () => { await api(`/api/friends/${f.id}`, { method: "DELETE" }); refreshAll(); },
            { confirm: `Remove ${f.display_name} from your friends? They'll also be removed from your friend groups.`, success: "Friend removed" }) }, "Unfriend")),
        "No friends yet. Search above to send a request.");
    } catch (err) { showLoadError(friends, err); }
  }

  loadIncoming();
  loadOutgoing();
  loadFriends();
})();

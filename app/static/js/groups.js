(function () {
  const { api, h, showLoadError, action, bindForm, toast } = window.Tripzy;
  const container = document.getElementById("group-list");
  const createForm = document.getElementById("group-form");
  let friends = [];

  bindForm(createForm, async (values) => {
    await api("/api/friend-groups", { method: "POST", body: { name: values.name } });
    createForm.reset();
    toast("Group created");
    load();
  });

  function groupCard(g) {
    const memberIds = new Set(g.members.map((m) => m.id));
    const available = friends.filter((f) => !memberIds.has(f.id));

    const renameForm = h("form", { class: "inline-form", method: "post", novalidate: true },
      h("div", { class: "field grow" },
        h("label", { for: `rename-${g.id}` }, "Group name"),
        h("input", { id: `rename-${g.id}`, name: "name", value: g.name, maxlength: 100, required: true })),
      h("button", { class: "btn", type: "submit" }, "Rename"));
    bindForm(renameForm, async (values) => {
      await api(`/api/friend-groups/${g.id}`, { method: "PATCH", body: { name: values.name } });
      toast("Group renamed");
      load();
    });

    const select = h("select", { id: `add-${g.id}`, name: "user_id" },
      h("option", { value: "" }, available.length ? "— Choose a friend —" : "All your friends are in this group"),
      available.map((f) => h("option", { value: f.id }, `${f.display_name} (${f.email})`)));
    const addForm = h("form", { class: "inline-form", method: "post", novalidate: true },
      h("div", { class: "field grow" }, h("label", { for: `add-${g.id}` }, "Add a friend"), select),
      h("button", { class: "btn btn-primary", type: "submit", disabled: !available.length }, "Add"));
    bindForm(addForm, async (values) => {
      if (!values.user_id) throw new Tripzy.ApiError("Choose a friend to add", 422, "VALIDATION_ERROR", "user_id");
      await api(`/api/friend-groups/${g.id}/members`, { method: "POST", body: { user_id: Number(values.user_id) } });
      toast("Friend added to group");
      load();
    });

    const members = h("ul", { class: "list" },
      g.members.length
        ? g.members.map((m) => h("li", {},
            h("div", { class: "grow" }, h("div", { class: "title" }, m.display_name), h("div", { class: "sub" }, m.email)),
            h("button", { class: "btn btn-small", type: "button", onclick: (e) =>
              action(e.currentTarget, async () => { await api(`/api/friend-groups/${g.id}/members/${m.id}`, { method: "DELETE" }); load(); },
                { confirm: `Remove ${m.display_name} from ${g.name}? They stay your friend.`, success: "Removed from group" }) }, "Remove")))
        : h("li", { class: "empty" }, "No members yet."));

    return h("section", { class: "card", "aria-labelledby": `group-${g.id}-title` },
      h("div", { class: "card-head" },
        h("h2", { id: `group-${g.id}-title` }, g.name, " ", h("span", { class: "badge" }, `${g.members.length} member${g.members.length === 1 ? "" : "s"}`)),
        h("button", { class: "btn btn-small btn-danger", type: "button", onclick: (e) =>
          action(e.currentTarget, async () => { await api(`/api/friend-groups/${g.id}`, { method: "DELETE" }); load(); },
            { confirm: `Delete the group "${g.name}"? Friendships are not affected.`, success: "Group deleted" }) }, "Delete group")),
      members,
      h("div", { class: "row" }, addForm, renameForm));
  }

  async function load() {
    try {
      const [groups, friendList] = await Promise.all([api("/api/friend-groups"), api("/api/friends")]);
      friends = friendList;
      container.removeAttribute("aria-busy");
      container.replaceChildren(...(groups.length ? groups.map(groupCard) : [h("p", { class: "muted" }, "No groups yet. Create one above.")]));
    } catch (err) { showLoadError(container, err); }
  }

  load();
})();

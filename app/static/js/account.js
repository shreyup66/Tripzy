(function () {
  const { api, bindForm, toast } = window.Tripzy;

  bindForm(document.getElementById("profile-form"), async (values) => {
    await api("/api/account", { method: "PATCH", body: { display_name: values.display_name, email: values.email } });
    toast("Profile updated");
    setTimeout(() => location.reload(), 600);
  });

  bindForm(document.getElementById("password-form"), async (values, form) => {
    await api("/api/account", {
      method: "PATCH",
      body: { current_password: values.current_password, new_password: values.new_password },
    });
    form.reset();
    toast("Password changed");
  });
})();

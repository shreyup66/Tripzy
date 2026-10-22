(function () {
  const { api, bindForm } = window.Tripzy;

  function nextUrl() {
    const next = new URLSearchParams(location.search).get("next") || "";
    // Only allow same-site paths, never "//evil.example".
    return next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
  }

  bindForm(document.getElementById("login-form"), async (values) => {
    await api("/api/auth/login", { method: "POST", body: { email: values.email, password: values.password } });
    location.href = nextUrl();
  });

  bindForm(document.getElementById("signup-form"), async (values) => {
    await api("/api/auth/signup", {
      method: "POST",
      body: { display_name: values.display_name, email: values.email, password: values.password },
    });
    location.href = "/dashboard";
  });
})();

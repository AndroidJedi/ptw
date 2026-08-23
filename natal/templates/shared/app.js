document.querySelectorAll('[data-year]').forEach((node) => {
  node.textContent = String(new Date().getFullYear());
});

document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener('click', (event) => {
    const selector = link.getAttribute('href');
    if (!selector || selector.length < 2) return;
    const target = document.getElementById(selector.slice(1));
    if (!target) return;
    event.preventDefault();
    target.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  });
});

document.querySelectorAll('[data-natal-lead]').forEach((form) => {
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const status = form.querySelector('.form-status');
    const endpoint = form.dataset.endpoint;
    if (!endpoint || !form.reportValidity()) return;
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    status.textContent = '';
    status.removeAttribute('data-state');
    const body = Object.fromEntries(new FormData(form).entries());
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error('submission failed');
      form.reset();
      status.textContent = status.dataset.success;
      status.dataset.state = 'success';
    } catch (_) {
      status.textContent = document.documentElement.lang === 'uk'
        ? 'Не вдалося надіслати. Спробуйте ще раз.'
        : 'Could not submit. Please try again.';
      status.dataset.state = 'error';
      button.disabled = false;
    }
  });
});

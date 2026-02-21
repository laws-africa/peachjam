class UserAuth {
  constructor (root: HTMLElement) {
    const codeSection = root.querySelector('#code-section') as HTMLElement | null;
    const passwordSection = root.querySelector('#password-section') as HTMLElement | null;
    const showPasswordBtn = root.querySelector('#show-password-btn') as HTMLElement | null;
    const showCodeBtn = root.querySelector('#show-code-btn') as HTMLElement | null;

    function toggle (hide: HTMLElement, show: HTMLElement) {
      hide.style.display = 'none';
      show.style.display = 'block';
    }

    if (showPasswordBtn && codeSection && passwordSection) {
      showPasswordBtn.addEventListener('click', function (e) {
        e.preventDefault();
        toggle(codeSection, passwordSection);
      });
    }

    if (showCodeBtn && codeSection && passwordSection) {
      showCodeBtn.addEventListener('click', function (e) {
        e.preventDefault();
        toggle(passwordSection, codeSection);
      });
    }
  }
}

export default UserAuth;

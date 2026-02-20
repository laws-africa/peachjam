class UserAuth {
  constructor (root: HTMLElement) {
    const codeSection = root.querySelector('#code-section') as HTMLElement | null;
    const passwordSection = root.querySelector('#password-section') as HTMLElement | null;
    const showPasswordBtn = root.querySelector('#show-password-btn') as HTMLElement | null;
    const showCodeBtn = root.querySelector('#show-code-btn') as HTMLElement | null;
    const pwContinueBtn = root.querySelector('#pw-continue-btn') as HTMLElement | null;

    function toggle (hide: HTMLElement, show: HTMLElement) {
      hide.style.display = 'none';
      show.style.display = 'block';
    }

    if (showPasswordBtn && codeSection && passwordSection) {
      showPasswordBtn.onclick = function (e) {
        e.preventDefault();
        toggle(codeSection, passwordSection);
      };
    }

    if (showCodeBtn && codeSection && passwordSection) {
      showCodeBtn.onclick = function (e) {
        e.preventDefault();
        toggle(passwordSection, codeSection);
      };
    }

    if (pwContinueBtn) {
      const p1Id = root.getAttribute('data-password1-id');
      const p2Id = root.getAttribute('data-password2-id');
      const mismatchMsg = root.getAttribute('data-mismatch-msg') || 'Passwords do not match.';

      pwContinueBtn.onclick = function () {
        const p1 = p1Id ? document.getElementById(p1Id) as HTMLInputElement | null : null;
        const p2 = p2Id ? document.getElementById(p2Id) as HTMLInputElement | null : null;
        if (!p1 || !p2) return;

        if (!p1.value || !p2.value) {
          if (!p1.value) p1.classList.add('is-invalid');
          if (!p2.value) p2.classList.add('is-invalid');
          return;
        }

        if (p1.value !== p2.value) {
          p2.classList.add('is-invalid');
          let fb = p2.parentElement?.querySelector('.invalid-feedback') as HTMLElement | null;
          if (!fb) {
            fb = document.createElement('div');
            fb.className = 'invalid-feedback';
            p2.parentElement?.appendChild(fb);
          }
          fb.textContent = mismatchMsg;
          return;
        }

        p1.classList.remove('is-invalid');
        p2.classList.remove('is-invalid');
        const step1 = document.getElementById('pw-step1');
        const step2 = document.getElementById('pw-step2');
        if (step1 && step2) {
          toggle(step1, step2);
        }
      };
    }
  }
}

export default UserAuth;

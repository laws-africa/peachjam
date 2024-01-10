const debounce = (func, wait, immediate) => {
  let timeout;
  return function () {
    const context = this; const args = arguments;
    const later = function () {
      timeout = null;
      if (!immediate) func.apply(context, args);
    };
    const callNow = immediate && !timeout;
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
    if (callNow) func.apply(context, args);
  };
};

function getCaseNumbers () {
  const visible = {};
  const hidden = {};
  const inputs = document.querySelectorAll("input[name^='case_numbers-'], select[name^='case_numbers-']");
  inputs.forEach(input => {
    if (input.type === 'hidden') {
      hidden[input.name] = input.value;
    } else {
      visible[input.name] = input.value;
    }
  });
  return { visible, hidden };
}

function getCSRFToken () {
  const cookies = document.cookie.split(';');
  const cookie = cookies.find(cookie => cookie.trim().startsWith('csrftoken'));
  return cookie.split('=')[1];
}

function getJudgmentId () {
  let judgmentId = '';
  const currentPath = window.location.pathname;
  if (currentPath.includes('/change/')) {
    judgmentId = currentPath.match(/\/judgment\/(\d+)\/change\/$/)[1];
  }
  return judgmentId;
}

function checkDuplicates () {
  const court = document.querySelector("[name='court']").value;
  const day = document.querySelector("[name='date_0']").value;
  const month = document.querySelector("[name='date_1']").value;
  const year = document.querySelector("[name='date_2']").value;
  const caseNumbers = getCaseNumbers();

  if (court && day && month && year && Object.values(caseNumbers.visible).some(Boolean)) {
    const date = year + '-' + month + '-' + day;
    const form = new FormData();
    form.set('judgment_id', getJudgmentId());
    form.set('court', court);
    form.set('date', date);
    form.set('csrfmiddlewaretoken', getCSRFToken());
    for (const [key, value] of Object.entries({ ...caseNumbers.visible, ...caseNumbers.hidden })) {
      form.set(key, value);
    }

    fetch('/api/check-duplicates/', {
      method: 'post',
      body: form
    }).then(response => {
      if (response.ok) {
        return response.text();
      } else {
        throw new Error('Something went wrong');
      }
    }).then(data => {
      const container = document.querySelector('#duplicate-alert-container');
      container.innerHTML = '';
      container.innerHTML = data;
    }).catch(error => {
      console.log(error);
    });
  }
}

document.addEventListener('DOMContentLoaded', function () {
  const actionsBlock = document.querySelector('#jazzy-actions div:first-child');
  const duplicateAlertContainer = document.createElement('div');
  duplicateAlertContainer.setAttribute('id', 'duplicate-alert-container');
  actionsBlock.prepend(duplicateAlertContainer);

  $('#case_numbers-group, #key-details-tab').on('change',
    "[name^='case_numbers-']:input, " +
      "[name^='case_numbers-'] select, " +
      "[name='court'], [name='date_0'], " +
      "[name='date_1'], [name='date_2']",
    debounce(checkDuplicates, 3000)
  );
});

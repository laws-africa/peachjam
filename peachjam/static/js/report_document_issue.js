function handleResponse (reportForm, response, url) {
  const modalLabel = document.getElementById('reportModalLabel');
  modalLabel.textContent = '';
  reportForm.innerHTML = '';
  reportForm.innerHTML = response;
}

const reportForm = document.getElementById('report-form');
const form = new FormData(reportForm);
const url = new URL(window.location.href);

reportForm.addEventListener('submit', (event) => {
  event.preventDefault();

  fetch('/api/document-problem/', {
    method: 'post',
    body: form
  }).then(response => {
    if (response.ok) {
      return response.text();
    } else {
      throw new Error('Something went wrong');
    }
  }).then(data => {
    handleResponse(reportForm, data, url);
  }).catch(error => {
    console.log(error);
  });
});

import { manager } from './manager';

export { default as OfflineDetails } from './OfflineDetails.vue';
export { default as OfflineTaxonomyStatus } from './OfflineTaxonomyStatus.vue';

export class OfflineTaxonomyButton {
  constructor (button: HTMLElement) {
    const id = button.getAttribute('data-taxonomy');
    const status = button.getAttribute('data-status');
    const statusDiv = status ? document.querySelector(status) : null;

    if (id) {
      button.addEventListener('click', async (event: Event) => {
        const url = document.location.pathname;

        if (statusDiv) {
          // Initialize the progress bar
          statusDiv.innerHTML = `
            <div class="progress">
              <div class="progress-bar" role="progressbar" style="width: 0%;" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100"></div>
            </div>
          `;
          const progressBar = statusDiv.querySelector('.progress-bar') as HTMLElement;

          let completed = 0;
          let total = 1; // Default total to avoid division by zero

          for await (const result of manager.makeTaxonomyAvailableOfflineDetails(id)) {
            if (result.total) total = result.total;
            completed = result.completed;

            const percentage = Math.round((completed / total) * 100);
            progressBar.style.width = `${percentage}%`;
            progressBar.textContent = `${percentage}%`;
            progressBar.setAttribute('aria-valuenow', `${percentage}`);
          }
        } else {
          manager.makeTaxonomyAvailableOffline(id);
        }
      });
    }
  }
}

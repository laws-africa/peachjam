export default class TopicCourtBalance {
  topicList: HTMLElement | null;
  courtList: HTMLElement | null;
  topicRows: HTMLElement[];
  courtPanels: HTMLElement[];

  constructor (root: HTMLElement) {
    this.topicList = root.querySelector('[data-topic-court-balance-topic-list]');
    this.courtList = root.querySelector('[data-topic-court-balance-court-list]');
    this.topicRows = Array.from(
      root.querySelectorAll<HTMLElement>('[data-topic-court-balance-topic]')
    );
    this.courtPanels = Array.from(
      root.querySelectorAll<HTMLElement>('[id^="courts-for-"]')
    );

    this.courtPanels.forEach((panel) => {
      panel.addEventListener('shown.bs.collapse', () => this.balanceTopics());
      panel.addEventListener('hidden.bs.collapse', () => this.balanceTopics());
    });
    window.addEventListener('resize', () => this.balanceTopics());
    this.balanceTopics();
  }

  resetTopics () {
    this.topicRows.forEach((row) => {
      row.classList.toggle('d-none', row.dataset.defaultVisible !== 'true');
    });
  }

  balanceTopics () {
    this.resetTopics();
    if (!this.topicList || !this.courtList) return;

    const anyCourtOpen = this.courtPanels.some((panel) =>
      panel.classList.contains('show')
    );
    if (!anyCourtOpen) return;

    for (const row of this.topicRows) {
      if (row.dataset.defaultVisible === 'true') continue;
      if (this.topicList.offsetHeight >= this.courtList.offsetHeight) break;
      row.classList.remove('d-none');
    }
  }
}

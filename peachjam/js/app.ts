import peachJam from './peachjam';
import * as bootstrap from 'bootstrap';

declare global {
  interface Window {
    bootstrap?: any;
  }
}
window.bootstrap = bootstrap;

(() => {
  // @ts-ignore
  window.peachjam = peachJam;
  peachJam.setup();
})();

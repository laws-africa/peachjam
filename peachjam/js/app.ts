import peachJam from './peachjam';
import * as bootstrap from 'bootstrap';

declare global {
  interface Window {
    bootstrap?: any;
  }
}
window.bootstrap = bootstrap;

(() => {
  peachJam.setup();
})();

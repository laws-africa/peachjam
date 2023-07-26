import peachJam from './peachjam';
import * as bootstrap from '../static/bootstrap/dist/js/bootstrap.bundle.js';

declare global {
  interface Window {
    bootstrap?: any;
  }
}
window.bootstrap = bootstrap;

(() => {
  peachJam.setup();
})();

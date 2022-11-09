// Reusable utility functions

export function scrollToElement (elem: HTMLElement, callback: (element: HTMLElement) => void = () => false, offset: number = 0) {
  // Setup intersection observer
  const observer = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        observer.unobserve(entry.target);
        // If intersect element run callback and unobserve
        window.setTimeout(() => {
          callback(elem);
        }, 500);
      }
    });
  });
  observer.observe(elem);

  const rect = elem.getBoundingClientRect();
  const targetPosition = Math.floor(rect.top + self.pageYOffset - offset);

  window.scrollTo({
    top: targetPosition,
    behavior: 'smooth'
  });
  // if scroll interrupted, cancel observation
  let isScrolling:ReturnType<typeof setTimeout>;

  const clearFn = () => {
    // Clear our timeout throughout the scroll
    window.clearTimeout(isScrolling);

    // Set a timeout to run after scrolling ends
    isScrolling = setTimeout(function () {
      // Unobserve element
      observer.unobserve(elem);
      // Remove listener after unobserve
      window.removeEventListener('scroll', clearFn);
    }, 66);
  };

  // Listen for scroll events
  window.addEventListener('scroll', clearFn, false);
}

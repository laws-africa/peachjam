// Reusable utility functions

import { TOCItemType } from './types-and-interfaces';

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

export const generateHtmlTocItems = (content: HTMLElement) => {
  let stack: any;
  const items: TOCItemType[] = [];

  content.querySelectorAll<HTMLElement>('h1, h2, h3, h4, h5').forEach((heading) => {
    if (!heading.id) {
      heading.id = heading.tagName + '_' + Math.floor(Math.random() * 10000);
    }

    const item = {
      type: heading.tagName,
      title: heading.innerText,
      id: heading.id,
      children: []
    };

    // top level
    if (!stack) {
      items.push(item);
      stack = [item];
    } else {
      // find the best sibling for this entry; if the stack is at h3 and we have h2, find an h2 or h1
      while (stack.length && stack[stack.length - 1].type > heading.tagName) {
        stack.pop();
      }
      const top = stack[stack.length - 1];

      if (top.type === heading.tagName) {
        // siblings
        if (stack.length > 1) {
          stack[stack.length - 2].children.push(item);
        } else {
          items.push(item);
        }
        stack[stack.length - 1] = item;
      } else {
        // child
        top.children.push(item);
        stack.push(item);
      }
    }
  });
  return items;
};

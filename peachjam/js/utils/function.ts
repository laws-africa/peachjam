// Reusable utility functions

import { TOCItemType } from './types-and-interfaces';

export function scrollToElement (elem: HTMLElement, callback: (element: HTMLElement) => void = () => false, offset: number = 0) {
  if (window.IntersectionObserver === undefined) return;

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

/**
 * Infer a table of contents (in the form of a list of TOC items) for general HTML, based h* tags.
 */
export function generateHtmlTocItems (content: HTMLElement): TOCItemType[] {
  let stack: any;
  const items: TOCItemType[] = [];
  const ids = new Map<string, number>();

  content.querySelectorAll<HTMLElement>('h1, h2, h3, h4, h5').forEach((heading) => {
    if (!heading.id) {
      ids.set(heading.tagName, (ids.get(heading.tagName) || 0) + 1);
      heading.id = heading.tagName + '_' + ids.get(heading.tagName);
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

      if (top) {
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
    }
  });

  return items;
}

/**
 * Ensure the HTML covered by these TOC items are wrapped in nested divs.
 */
export function wrapTocItems (root: HTMLElement, items: TOCItemType[]) {
  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    const nextItem = i + 1 < items.length ? items[i + 1] : null;
    const nextId: string | null = nextItem ? nextItem.id : null;
    const el: HTMLElement | null = document.getElementById(item.id);

    if (el) {
      const wrapper = document.createElement('div');
      wrapper.id = item.id;
      el.removeAttribute('id');
      el.parentElement?.insertBefore(wrapper, el);

      // wrap all content from this heading to the next in a div
      // keep going until we run out of elements, or we hit the next TOC item
      let node: Node | null = el;
      // eslint-disable-next-line no-unmodified-loop-condition
      while (node && !(node instanceof HTMLElement && nextId != null && (node as HTMLElement).id === nextId)) {
        const nextEl: Node | null = node.nextSibling;
        wrapper.appendChild(node);
        node = nextEl;
      }

      if (item.children) {
        wrapTocItems(wrapper, item.children);
      }
    }
  }
}

export const createTocController = (items: [] = []) => {
  const laTocController = document.createElement('la-table-of-contents-controller');
  laTocController.items = items;
  laTocController.expandAllBtnClasses = 'btn btn-secondary btn-sm';
  laTocController.collapseAllBtnClasses = 'btn btn-secondary btn-sm';
  laTocController.titleFilterInputClasses = 'form-control';
  laTocController.titleFilterClearBtnClasses = 'btn btn-secondary btn-sm';
  return laTocController;
};

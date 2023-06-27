import { toRange as textPositionToRange, fromRange as textPositionFromRange } from 'dom-anchor-text-position';
import { toRange as textQuoteToRange, fromTextPosition as textQuoteFromTextPosition } from 'dom-anchor-text-quote';

// Selector for elements that are foreign to AKN documents, such as table editor buttons
// and annotations
const foreignElementsSelector = '.tausi';

export const getTextNodes = (range) => {
  const textNodes = [];
  const ignore = {
    TABLE: 1,
    THEAD: 1,
    TBODY: 1,
    TR: 1
  };
  let iterator, node, posn, start, end;

  function split (node, offset) {
    // split the text node so that the offsets fall on text node boundaries
    if (offset !== 0) {
      return node.splitText(offset);
    } else {
      return node;
    }
  }

  node = range.commonAncestorContainer;
  if (node.nodeType !== Node.ELEMENT_NODE) {
    node = node.parentElement;
  }

  // remove foreign elements while working with the range
  withoutForeignElements(node, function () {
    if (range.startContainer.nodeType === Node.TEXT_NODE) {
      // split the start and end text nodes so that the offsets fall on text node boundaries
      start = split(range.startContainer, range.startOffset);
    } else {
      // first text node
      start = document.createNodeIterator(range.startContainer, NodeFilter.SHOW_TEXT).nextNode();
      if (!start) return;
    }

    if (range.endContainer.nodeType === Node.TEXT_NODE) {
      end = split(range.endContainer, range.endOffset);
    } else {
      end = range.endContainer;
    }

    // gather all the text nodes between start and end
    iterator = document.createNodeIterator(
      range.commonAncestorContainer, NodeFilter.SHOW_TEXT,
      function (n) {
        // ignore text nodes in weird positions in tables
        if (ignore[n.parentElement.tagName]) return NodeFilter.FILTER_SKIP;
        return NodeFilter.FILTER_ACCEPT;
      });

    // advance until we're at the start node
    node = iterator.nextNode();
    while (node && node !== start) node = iterator.nextNode();

    // gather text nodes
    while (node) {
      posn = node.compareDocumentPosition(end);
      // stop if node isn't inside end, and doesn't come before end
      if ((posn & Node.DOCUMENT_POSITION_CONTAINS) === 0 &&
        (posn & Node.DOCUMENT_POSITION_FOLLOWING) === 0) break;

      textNodes.push(node);
      node = iterator.nextNode();
    }
  });

  return textNodes;
};

/**
 * Mark all the text nodes in a range with a given tag (eg. 'mark'),
 * calling the callback for each new marked element.
 */
export function markRange (range, tagName, callback, creator) {
  const tag = tagName || 'mark';

  const textNodes = getTextNodes(range);

  // mark the gathered nodes
  textNodes.forEach(function (textNode) {
    let mark = creator ? creator(textNode, tag) : textNode.ownerDocument.createElement(tag);
    if (mark) {
      if (callback) {
        // let the callback modify the mark
        mark = callback(mark, textNode);
      }
      if (mark) {
        textNode.parentElement.insertBefore(mark, textNode);
        mark.appendChild(textNode);
      }
    }
  });
}

/**
 * Removes foreign elements from the tree at root, executes callback,
 * and then replaces the foreign elements.
 *
 * This is useful for annotations because we inject foreign (ie. non-Akoma Ntoso)
 * elements into the rendered AKN document, such as table editor buttons, annotations
 * and issue indicators.
 *
 * @returns the result of callback()
 */
export function withoutForeignElements (root, callback, selector) {
  const removed = [];

  selector = selector || foreignElementsSelector;

  // remove the foreign elements
  root.querySelectorAll(selector).forEach(function (elem) {
    const info = { e: elem };

    // store where the element was in the tree
    if (elem.nextSibling) info.before = elem.nextSibling;
    // no next sibling, it's the last child
    else info.parent = elem.parentElement;

    elem.parentElement.removeChild(elem);
    removed.push(info);
  });

  let result;
  try {
    result = callback();
  } finally {
    // put the elements back, even if result throws an error
    removed.reverse();
    removed.forEach(function (info) {
      if (info.before) info.before.parentElement.insertBefore(info.e, info.before);
      else info.parent.appendChild(info.e);
    });
  }

  return result;
}

/**
 * Convert a Target object (anchor_id, selectors) to Range object.
 *
 * This does its best to try to find a match, walking up the anchor hierarchy if possible.
 */
export function targetToRange (target, root) {
  let anchorId = target.anchor_id;
  let ix = anchorId.lastIndexOf('__');
  let anchor = root.querySelector(`[id="${anchorId}"]`);

  // do our best to find the anchor node, going upwards up the id chain if
  // the id has dotted components
  while (!anchor && ix > -1) {
    anchorId = anchorId.substring(0, ix);
    ix = anchorId.lastIndexOf('__');
    anchor = root.querySelector(`[id="${anchorId}"]`);
  }

  if (!anchor) return;

  // remove foreign elements, then use the selectors to find the text and build up a Range object.
  return withoutForeignElements(anchor, () => {
    return selectorsToRange(anchor, target.selectors);
  });
}

/**
 * Given a root and a list of selectors, create browser Range object.
 *
 * Only TextPositionSelector and TextQuoteSelector types from https://www.w3.org/TR/annotation-model/
 * are used.
 */
export function selectorsToRange (anchor, selectors) {
  let range;
  const posnSelector = selectors.find((x) => x.type === 'TextPositionSelector');
  const quoteSelector = selectors.find((x) => x.type === 'TextQuoteSelector');

  if (posnSelector) {
    try {
      range = textPositionToRange(anchor, posnSelector);
      // compare text with the exact from the quote selector
      if (quoteSelector && range.toString() === quoteSelector.exact) {
        return range;
      }
    } catch (err) {
      // couldn't match to the position, try the quote selector instead
    }
  }

  // fall back to the quote selector
  if (quoteSelector) {
    return textQuoteToRange(anchor, quoteSelector);
  }
}

/**
 * Given a browser Range object, transform it into a target description
 * suitable for use with annotations. Will not go above root, if given.
 */
export function rangeToTarget (range, root) {
  let anchor = range.commonAncestorContainer;
  const target = { selectors: [] };

  // find the closest element to this anchor that has an id attribute
  if (anchor.nodeType !== Node.ELEMENT_NODE) anchor = anchor.parentElement;
  anchor = anchor.closest('[id]');

  if (root && anchor !== root &&
    (anchor.compareDocumentPosition(root) & Node.DOCUMENT_POSITION_CONTAINS) === 0) return;
  target.anchor_id = anchor.id;

  withoutForeignElements(anchor, () => {
    // position selector
    let selector = textPositionFromRange(anchor, range);
    selector.type = 'TextPositionSelector';
    target.selectors.push(selector);

    // quote selector, based on the position
    selector = textQuoteFromTextPosition(anchor, selector);
    selector.type = 'TextQuoteSelector';
    target.selectors.push(selector);
  });

  return target;
}

/**
 * Return the index of this node in its parent's list of children.
 */
export function elementIndex (node) {
  let i = 0;
  while ((node = node.previousElementSibling) != null) i++;
  return i;
}

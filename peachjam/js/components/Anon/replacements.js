import { getTextNodes, rangeToTarget, targetToRange } from '@lawsafrica/indigo-akn/dist/ranges';
import Mark from 'mark.js';

let counter = 0;

export class Replacement {
  constructor (root, oldText, newText, target, suggestion, applied) {
    this.id = counter++;
    this.root = root;
    this.oldText = oldText;
    this.newText = newText;
    this.target = target;
    this.applied = applied;
    this.suggestion = suggestion;
    this.marks = [];
  }

  apply () {
    if (!this.applied) {
      const range = this.toRange();
      if (range) {
        this.target = rangeToTarget(this.replaceWithText(range, this.newText), this.root);
        this.applied = true;
      }
    }
  }

  unapply () {
    if (this.applied) {
      const range = this.toRange();
      if (range) {
        this.target = rangeToTarget(this.replaceWithText(range, this.oldText), this.root);
        this.applied = false;
      }
    }
  }

  toRange () {
    return targetToRange(this.target, this.root);
  }

  replaceWithText(range, text) {
    const node = document.createTextNode(text);

    // insert the text at the start of the range, rather than deleting the contents and then inserting it, which
    // puts the text at the "end" which may be on a new line (i.e. past the end of the element)
    range.insertNode(node);
    range.setStartAfter(node);
    range.deleteContents();

    const newRange = document.createRange();
    newRange.setStartBefore(node);
    newRange.setEndAfter(node);

    node.parentElement.normalize();

    return newRange;
  }

  mark () {
    this.unmark();

    const range = this.toRange();
    if (range) {
      for (const textNode of getTextNodes(range)) {
        if (textNode.parentElement) {
          let mark = textNode.ownerDocument.createElement('mark');
          textNode.parentElement.insertBefore(mark, textNode);
          mark.appendChild(textNode);
          mark.classList.toggle('applied', this.applied);
          mark._replacement = this;
          this.marks.push(mark);
        }
      }
    }
  }

  unmark () {
    for (const mark of this.marks) {
      unwrap(mark);
    }
    this.marks = [];
  }

  snippet () {
    const sel = this.target.selectors.find((s) => s.type === 'TextQuoteSelector');
    const len = 15;

    if (sel) {
      return `... ${sel.prefix.slice(-len)}<mark>${sel.exact}</mark>${sel.suffix.slice(0, len)} ...`;
    } else {
      return this.oldtext;
    }
  }

  grouping () {
    return this.oldText + ' → ' + this.newText;
  }

  serialise () {
    return {
      old_text: this.oldText,
      new_text: this.newText,
      target: this.target
    };
  }
}

export class ReplacementGroup {
  constructor (replacements) {
    this.key = replacements[0].grouping();
    this.title = this.key;
    this.replacements = replacements;
    this.suggestions = [];
  }

  populateSuggestions () {
    // remove old suggestions, calling unmark() on them before doing so
    for (const replacement of this.suggestions) {
      replacement.unmark();
    }

    this.suggestions.splice(0, this.suggestions.length);

    if (this.replacements.length > 0) {
      const first = this.replacements[0];

      for (const range of this.findSuggestions(first.root, first.oldText)) {
        const replacement = new Replacement(
          first.root,
          range.toString(),
          first.newText,
          rangeToTarget(range, first.root),
          true,
        );
        this.suggestions.push(replacement);
      }
    }
  }

  /**
   * Find possible occurrences of this range in the root element, ignoring anything in <mark> tags
   * @returns array of Range objects
   */
  findSuggestions (root, oldText) {
    let text = oldText;
    let marker = new Mark(root);

    const ranges = [];
    const marks = [];

    if (!RegExp.escape) {
      text = text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    } else {
      text = RegExp.escape(text);
    }

    const re = new RegExp('\\b' + text + '\\b', 'g');

    marker.markRegExp(re, {
      acrossElements: true,
      exclude: ["mark"],
      each: (mark) => {
        marks.push(mark);
      }
    });

    // combine adjacent marks that don't have the whole text
    let range;
    for (let i = 0; i < marks.length; i++) {
      const mark = marks[i];

      if (range && range.toString().length < text.length) {
        // combine with existing range
        range.setEndAfter(mark);
        unwrap(mark);
        continue;
      }

      if (range && range.toString().length >= text.length) {
        // we have a complete range
        ranges.push(range);
        range = null;
      }

      if (!range) {
        range = document.createRange();
        range.setStartBefore(mark);
        range.setEndAfter(mark);
      }

      unwrap(mark);
    }

    if (range) {
      ranges.push(range);
    }

    return ranges;
  }
}

export function unwrap(el) {
  const parent = el.parentElement;
  while (parent && el.firstChild) {
    parent.insertBefore(el.firstChild, el);
  }
  el.remove();
}

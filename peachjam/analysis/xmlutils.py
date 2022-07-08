def wrap_text(node, tail, wrapper, start_pos=None, end_pos=None):
    """Wrap the text (or tail if tail is True) of a node in wrapper (a callable).
    Optionally, start_pos and end_pos specify the substring of the node's text (or tail)
    to be wrapped. The wrapper callable will be called with the text being wrapped.
    """
    if tail:
        text = node.tail or ""
        start_pos = start_pos or 0
        end_pos = len(text) if end_pos is None else end_pos
        wrapped = wrapper(text[start_pos:end_pos])

        node.addnext(wrapped)
        node.tail = text[:start_pos]
        wrapped.tail = text[end_pos:]
    else:
        text = node.text or ""
        start_pos = start_pos or 0
        end_pos = len(text) if end_pos is None else end_pos
        wrapped = wrapper(text[start_pos:end_pos])

        node.text = text[:start_pos]
        node.insert(0, wrapped)
        wrapped.tail = text[end_pos:]

    return wrapped

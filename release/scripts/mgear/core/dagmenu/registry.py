"""Registry of the dag menu contexts and sections.

A context decides which kind of node was right-clicked (an mGear control, a
guide, ...). A section adds a group of menu items for one context. Sections
are built in ascending order, so other tools can insert items between the
built-in ones.

This module has no Maya dependency.
"""

import logging

logger = logging.getLogger("mgear.core.dagmenu")


class Context(object):
    """A kind of right-clicked node.

    Args:
        name (str): Context name. i.e: "control"
        detector (callable): Called with a MenuContext, returns True when the
            right-clicked node belongs to this context.
        priority (int, optional): Contexts are tested from the highest
            priority to the lowest.
        prepare (callable, optional): Called with the MenuContext before the
            sections are built. i.e: to register sections on demand.
    """

    def __init__(self, name, detector, priority=0, prepare=None):
        self.name = name
        self.detector = detector
        self.priority = priority
        self.prepare = prepare


class Section(object):
    """A group of menu items for one context.

    Args:
        context (str): Name of the context showing this section.
        name (str): Section name, unique in its context.
        order (int): Build order, lower first.
        build (callable): Called with a MenuBuilder and a MenuContext, adds
            the section items.
        poll (callable, optional): Called with a MenuContext, the section is
            skipped when it returns False.
    """

    def __init__(self, context, name, order, build, poll=None):
        self.context = context
        self.name = name
        self.order = order
        self.build = build
        self.poll = poll


class Registry(object):
    """Contexts and sections of the dag menu."""

    def __init__(self):
        self._contexts = {}
        self._sections = {}

    def register_context(self, name, detector, priority=0, prepare=None):
        """Register a context, replacing the one with the same name.

        Args:
            name (str): Context name.
            detector (callable): Called with a MenuContext, returns True when
                the right-clicked node belongs to this context.
            priority (int, optional): Contexts are tested from the highest
                priority to the lowest.
            prepare (callable, optional): Called with the MenuContext before
                the sections are built.

        Returns:
            Context: The registered context.
        """
        context = Context(name, detector, priority, prepare)
        self._contexts[name] = context
        return context

    def unregister_context(self, name):
        """Remove a context. Its sections are kept.

        Args:
            name (str): Context name.
        """
        self._contexts.pop(name, None)

    def register_section(self, context, name, order, build, poll=None):
        """Register a section, replacing the one with the same context and name.

        Args:
            context (str): Name of the context showing this section.
            name (str): Section name, unique in its context.
            order (int): Build order, lower first.
            build (callable): Called with a MenuBuilder and a MenuContext.
            poll (callable, optional): Called with a MenuContext, the section
                is skipped when it returns False.

        Returns:
            Section: The registered section.
        """
        section = Section(context, name, order, build, poll)
        self._sections[(context, name)] = section
        return section

    def unregister_section(self, context, name):
        """Remove a section.

        Args:
            context (str): Context name.
            name (str): Section name.
        """
        self._sections.pop((context, name), None)

    def contexts(self):
        """Get the contexts, highest priority first.

        Returns:
            list: Context objects.
        """
        return sorted(self._contexts.values(), key=lambda c: c.priority, reverse=True)

    def sections_for(self, context):
        """Get the sections of a context in build order.

        Args:
            context (str): Context name.

        Returns:
            list: Section objects.
        """
        sections = [s for s in self._sections.values() if s.context == context]
        return sorted(sections, key=lambda s: s.order)

    def detect(self, menu_context):
        """Get the name of the first context matching the right-clicked node.

        A detector raising an exception is logged and treated as no match.

        Args:
            menu_context (MenuContext): The right-click context.

        Returns:
            str: The context name, None when no context matches.
        """
        for context in self.contexts():
            try:
                if context.detector(menu_context):
                    return context.name
            except Exception:
                logger.exception("dag menu context '%s' detector failed", context.name)
        return None

    def build(self, builder, menu_context, context):
        """Build the sections of a context.

        Runs the context prepare function first. A prepare function or a
        section raising an exception is logged and skipped, the other
        sections are still built.

        Args:
            builder (MenuBuilder): Builder of the menu to fill.
            menu_context (MenuContext): The right-click context.
            context (str): Context name.
        """
        prepare = getattr(self._contexts.get(context), "prepare", None)
        if prepare:
            try:
                prepare(menu_context)
            except Exception:
                logger.exception("dag menu context '%s' prepare failed", context)
        for section in self.sections_for(context):
            try:
                if section.poll and not section.poll(menu_context):
                    continue
                builder.divider()
                section.build(builder, menu_context)
            except Exception:
                logger.exception(
                    "dag menu section '%s.%s' failed", context, section.name
                )

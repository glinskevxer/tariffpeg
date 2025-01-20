"""Guest review evidence pipeline for an accommodation standards unit.

The unit licenses serviced accommodation. Every licence carries a schedule of
particulars, which is the set of claims the operator registered: the bed count,
whether there is a lift, whether breakfast is included, how far the door is from
the shore. Guests write about those same things on booking channels. This
package harvests that writing under a documented fetch policy, turns it into
assertions about the particulars, and decides which licences need an inspector
sent out.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"

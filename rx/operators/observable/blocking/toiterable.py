import threading

from rx.core.blockingobservable import BlockingObservable
from rx.internal import Iterable, AnonymousIterable


def to_iterable(source: BlockingObservable) -> Iterable:
    """Returns an iterator that can iterate over items emitted by this
    `BlockingObservable`.

    Returns an iterable that can iterate over the items emitted by this
     `BlockingObservable`.
    """

    condition = threading.Condition()
    notifications = []

    def on_next(value):
        """Takes send values and appends them to the notification queue"""

        condition.acquire()
        notifications.append(value)
        condition.notify()  # signal that a new item is available
        condition.release()

    source.observable.materialize().subscribe_(on_next)

    def gen():
        """Generator producing values for the iterator"""

        while True:
            condition.acquire()
            while not notifications:
                condition.wait()
            notification = notifications.pop(0)

            if notification.kind == "E":
                raise notification.exception

            if notification.kind == "C":
                return  # StopIteration

            condition.release()
            yield notification.value

    return AnonymousIterable(gen())

from collections import OrderedDict

from rx.core import ObservableBase, AnonymousObservable, GroupedObservable
from rx.subjects import Subject
from rx.disposables import CompositeDisposable, RefCountDisposable, \
    SingleAssignmentDisposable
from rx.internal.basic import identity


def group_by_until(self, key_mapper, element_mapper, duration_mapper) -> ObservableBase:
    """Groups the elements of an observable sequence according to a
    specified key mapper function. A duration mapper function is used
    to control the lifetime of groups. When a group expires, it receives
    an OnCompleted notification. When a new element with the same key
    value as a reclaimed group occurs, the group will be reborn with a
    new lifetime request.

    1 - observable.group_by_until(
            lambda x: x.id,
            None,
            lambda : Rx.Observable.never()
        )
    2 - observable.group_by_until(
            lambda x: x.id,
            lambda x: x.name,
            lambda: Rx.Observable.never()
        )
    3 - observable.group_by_until(
            lambda x: x.id,
            lambda x: x.name,
            lambda:  Rx.Observable.never(),
            lambda x: str(x))

    Keyword arguments:
    key_mapper -- A function to extract the key for each element.
    duration_mapper -- A function to signal the expiration of a group.

    Returns a sequence of observable groups, each of which corresponds to
    a unique key value, containing all elements that share that same key
    value. If a group's lifetime expires, a new group with the same key
    value can be created once an element with such a key value is
    encountered.
    """

    source = self
    element_mapper = element_mapper or identity

    def subscribe(observer, scheduler=None):
        writers = OrderedDict()
        group_disposable = CompositeDisposable()
        ref_count_disposable = RefCountDisposable(group_disposable)

        def on_next(x):
            writer = None
            key = None

            try:
                key = key_mapper(x)
            except Exception as e:
                for wrt in writers.values():
                    wrt.on_error(e)

                observer.on_error(e)
                return

            fire_new_map_entry = False
            writer = writers.get(key)
            if not writer:
                writer = Subject()
                writers[key] = writer
                fire_new_map_entry = True

            if fire_new_map_entry:
                group = GroupedObservable(key, writer, ref_count_disposable)
                duration_group = GroupedObservable(key, writer)
                try:
                    duration = duration_mapper(duration_group)
                except Exception as e:
                    for wrt in writers.values():
                        wrt.on_error(e)

                    observer.on_error(e)
                    return

                observer.on_next(group)
                sad = SingleAssignmentDisposable()
                group_disposable.add(sad)

                def expire():
                    if writers[key]:
                        del writers[key]
                        writer.on_completed()

                    group_disposable.remove(sad)

                def on_next(value):
                    pass

                def on_error(exn):
                    for wrt in writers.values():
                        wrt.on_error(exn)
                    observer.on_error(exn)

                def on_completed():
                    expire()

                sad.disposable = duration.take(1).subscribe_(on_next, on_error, on_completed, scheduler)

            try:
                element = element_mapper(x)
            except Exception as error:
                for wrt in writers.values():
                    wrt.on_error(error)

                observer.on_error(error)
                return

            writer.on_next(element)

        def on_error(ex):
            for wrt in writers.values():
                wrt.on_error(ex)

            observer.on_error(ex)

        def on_completed():
            for wrt in writers.values():
                wrt.on_completed()

            observer.on_completed()

        group_disposable.add(source.subscribe_(on_next, on_error, on_completed, scheduler))
        return ref_count_disposable
    return AnonymousObservable(subscribe)

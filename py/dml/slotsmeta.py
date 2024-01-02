# © 2021-2024 Intel Corporation
# SPDX-License-Identifier: MPL-2.0

import abc
import inspect
import functools

__all__ = ['SlotsMeta',
           'auto_init']

class SlotsMeta(abc.ABCMeta):
    '''Metaclass for automatic slot assignment.

    All subclasses automatically gets __slots__ set. Subclasses that
    override __init__ define new slots based on __init__ arg names,
    and subclasses that don't override __init__ set __slots__ to ().

    Additional slots can be defined by setting the 'slots' attribute.

    The names of __init__ arguments of a class is accessible as an
    attribute 'init_args'.
    '''
    @staticmethod
    def patch_dict(dct, init_args, parent_init_args):
        dct['init_args'] = init_args
        assert init_args[:len(parent_init_args)] == parent_init_args
        dct['__slots__'] = (tuple(init_args[len(parent_init_args):])
                            + dct.get('slots', ()))

    def __new__(cls, clsname, bases, dct):
        if len(bases) > 1:
            all_inits = {base.__init__ for base in inspect.getmro(bases[0])}
            # permit multiple inheritance if all __init__ inheritance
            # is reachable from the first superclass, which
            # applied recursively means that inheritance on __init__ is linear
            for b in bases[1:]:
                for c in inspect.getmro(b):
                    assert c.__init__ in all_inits, c
        assert '__slots__' not in dct, "set 'slots' instead of '__slots__'"
        if '__init__' in dct:
            init = dct['__init__']
            parent_init_args = (bases[0].init_args
                                if bases and isinstance(bases[0], SlotsMeta)
                                else ['self'])
            # detect __init__() arglist. Introspection does not work
            # on the trampoline generated by @auto_init
            init_args = getattr(init, 'auto_init_args', None)
            if init_args:
                # auto_init does not work on base class
                assert bases and isinstance(bases[0], SlotsMeta)
                SlotsMeta.patch_dict(dct, init_args, parent_init_args)
                new_class = super(SlotsMeta, cls).__new__(
                    cls, clsname, bases, dct)
                init.cls = new_class
                return new_class
            else:
                (init_args, varargs, varkw, defaults, kwonlyargs,
                 kwonlydefaults, annotations) = inspect.getfullargspec(init)
                assert varargs is varkw is kwonlydefaults is None
                assert kwonlyargs == []
                assert annotations == {}
                SlotsMeta.patch_dict(dct, init_args, parent_init_args)
        else:
            dct['__slots__'] = dct.get('slots', ())
            assert isinstance(bases[0], SlotsMeta)
        return super(SlotsMeta, cls).__new__(cls, clsname, bases, dct)

def auto_init(fun):
    (args, varargs, varkw, defaults, kwonlyargs, kwonlydefaults,
     annotations) = inspect.getfullargspec(fun)
    assert varargs is varkw is kwonlydefaults is None
    assert not defaults
    assert kwonlyargs == []
    assert annotations == {}
    @functools.wraps(fun)
    def __init(*args, **kwargs):
        assert hasattr(__init, 'cls'), ('@auto_init only allowed in'
                                        ' SlotsMeta classes')
        cls = __init.cls
        self = args[0]
        sup = super(cls, self)
        super_nargs = len(sup.init_args)
        sup.__init__(*args[1:super_nargs])
        for (name, arg) in zip(self.init_args[super_nargs:],
                               args[super_nargs:]):
            setattr(self, name, arg)
        for (name, arg) in kwargs.items():
            setattr(self, name, arg)
        fun(*args, **kwargs)
    __init.auto_init_args = args
    return __init

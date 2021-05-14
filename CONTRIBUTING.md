## Contributing to mGear

### Argument shorthands

In Maya, some arguments have a short equivalent. Don't use it.

**Wrong**

```python
pm.workspace(q=True, rd=True)
```

**Right**

```python
pm.workspace(query=True, rootDirectory=True)
```

The reason is readability. The second reason is that these shorthands are provided not to make *your* code shorter, but to reduce the filesize of Maya's own internal scene format, the `.ma` files. It's not Pythonic, it's an optimisation.

<br>

### Members & `__init__`

Always declare all members of a class in the `__init__` method.

**Wrong**

```python
class MyClass(object):
    def __init__(self):
        super(MyClass, self).__init__()

        self.height = 5

    def resize(self, width, height):
        self.height = height
        self.width = width
```

**Right**

```python
class MyClass(object):
    def __init__(self):
        super(MyClass, self).__init__()

        self.height = 5
        self.width = 5

    def resize(self, width, height):
        self.height = height
        self.width = width
```

The reason is discoverability. When members are attached to `self` in any subsequent method, it becomes difficult to tell whether it is being created, or modified. More importantly, it becomes impossible to tell which member is used externally.

```python
from mymodule import MyClass

myclass = MyClass()
myclass.width = 5
print(myclass.other_member)
```

And at that point, impossible to maintain backwards compatibility should any of the methods creating new members be removed or refactored.

<br>

### Relative imports

Where possible, relatively reference the root mgear package.

**Wrong**

```python
from mgear.core import rigbits
```

**Right**

```python
from .maya import rigbits
```

This enables mgear to be bundled together with another library, e.g. `from .vendor.mgear import maya` and also avoids mgear being picked up from another location on a user's machine and PYTHONPATH. It also shortens the import line, which is always nice.

<br>

### Avoid `import as`

Where possible, avoid the use of `import ... as ...`.

```python
from mgear.core import rigbits as rb
```

This makes it more difficult to understand where a particular call is coming from, when read by someone who didn't initially make that import.

```python
swg.run_important_function()
# What does this do? :O
```

<br>

### Tuple versus List

Use List when mutability is required or intended, tuple otherwise.

```python
for item in ("good", "use", "of", "tuple"):
    pass
```

Tuples will tell you and the user when used them in an unintended way.

```python
# You
immutable = (1, 2, 3)

# User
immutable.append(4)
# ERROR
```

Whereas a list would not, and cause a difficult-to-debug error. The fabled "Works on my machine (tm)".

<br>

### Mutable arguments

Never use a mutable object in an argument signature.

```python
def function(wrong=[]):
    wrong.append(1)
    print(wrong)


function()
# [1]
function()
# [1, 1]
function()
# [1, 1, 1]
```

The same goes for `{}`. Instead, pass `None` and convert internally.

```python
def function(wrong=None):
    wrong = wrong or []
    wrong.append(1)
    print(wrong)

function()
# [1]
function()
# [1]
function()
# [1]
```

<br>

### Docstrings

All docstrings are written in Google Napoleon format.

```python
def function(a, b=True):
    """Summary here, no line breaks

    Long description here.

    Arguments:
        a (str): A first argument, mandatory
        b (bool, optional): A second argument

    Example:
        >>> print("A doctest")
        'A doctest'

    """
```

<br>

### Quotation Marks

Default to double-ticks, fallback to single-tick.

```python
# Right
side = "Right"

# Wrong
side = 'Left'

# Right
def function():
    """It's a single tick"""

# Wrong
def function():
    '''It's a single tick"""
```

<br>

### Code Style

We are refactoring all the code to [PEP8](https://www.python.org/dev/peps/pep-0008/)
If you want to contribute please follow the PEP8 standard

<br>

#### Ignore PEP8 Errors

"W503": [Break bfore or after binary operator](https://www.python.org/dev/peps/pep-0008/#should-a-line-break-before-or-after-a-binary-operator)

#### Line break for long arguments

```python

# No
function(arg1, arg2,
         kwarg=False, kwarg2=True)

# No
function(
    arg1, arg2,
    kwarg=False, kwarg2=True)

# Yes
function(arg1,
         arg2,
         kwarg=False,
         kwarg2=True)
# Yes
function(
    arg1, arg2, kwarg=False, kwarg2=True)

# OK
function(
    arg1,
    arg2,
    kwarg=False,
    kwarg2=True)

```
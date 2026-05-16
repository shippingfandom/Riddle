# Welcome to Riddle!
Riddle is a programming language that transpiles to Glosure.

## Syntax
Always end statements with a **semicolon**.

Code blocks are delimited by **braces**. Indentation matters only for readability.

Comments begin with **//**.

Conditions in **if**, **for**, **foreach** and **while** do NOT use parentheses around the condition — just write the expression directly.

## Control Flow

### if, else if, else
Use **if** blocks to branch on a condition. Include zero or more **else if** blocks and one optional **else** block.

```
if condition {
    body
} else if other_condition {
    other_body
} else {
    else_body
}
```

```
if a > b {
    print("a is bigger");
} elif a < b {
    print("b is bigger");
} else {
    print("equal");
}
```

### while
Use a **while** loop to repeat as long as a condition is true.

```
while condition {
    body
}
```

```
i = 0;
while i < 10 {
    print(i);
    i = i + 1;
}
```

### foreach
A **foreach** loop iterates over a collection, binding the index and value to variables.

```
foreach index value in collection {
    body
}
```

```
foreach idx val in ["apple", "banana", "cherry"] {
    print([idx, val]);
}
```

### for
A **for** loop repeats with an initializer, condition, and step expression.

```
for init; condition; step {
    body
}
```

```
for i = 0; i < 10; i = i + 1 {
    print(i);
}
```

## Data Types

### Booleans
Boolean values are **true** and **false**.

| Operators | Description |
|:----------|:------------|
| &&        | Logical AND |
| \|\|      | Logical OR  |
| !         | Logical NOT |
| ==, !=    | Equality    |

### Numbers
Numbers are stored in full precision.

| Operators | Description |
|:----------|:------------|
| +, -, *, / | Standard arithmetic |
| %          | Modulo |
| ^          | Power |
| ==, !=, >, >=, <, <= | Comparison |

### Strings
Strings are written in double quotes. Use **\\"** to include a literal quote inside the string. Other escape sequences like **\\n**, **\\t** and **\\\\** are also supported.

```
print("Hello \"world\"!");
```

| Operators | Description |
|:----------|:------------|
| [i]       | Get character at index *i* |

### null
The **null** value represents the absence of a value.

### Lists
Lists are written in square brackets. Access elements with a 0-based index.

```
list = [1, 2, 3];
print(list[0]); // 1
list[1] = 42;
```

| Operators | Description |
|:----------|:------------|
| [i]       | Get/set element at index *i* |

### Dictionaries
Dictionaries map string keys to values. Written in curly braces with **:** between key and value.

```
dict = {"name": "Riddle", "version": 1};
print(dict["name"]);
dict["version"] = 2;
```

| Operators | Description |
|:----------|:------------|
| [k]       | Get/set value with key *k* |

### Functions
Define a host function with **function** or Glosure function with **defun**. Parameters can have default values. The use of **return** is optional as Riddle returns the result of the latest expression.

```
function name(params) {
    body
}
```

```
function add(a, b = 0) {
    return a + b;
}

print(add(3, 4)); // 7
print(add(5));    // 5 (default b = 0)
```

Methods on namespaced objects use dot notation in the definition:

```
function namespace.functions.Hello() {
    print("Hello!");
}
```

### Anonymous Functions (glosure/lambda)
Create anonymous host function with **glosure** or anonymous Glosure function with **lambda**.

```
glosure (params) {
    body
}
```

```
apply = glosure (f, x) {
    return f(x);
};
```

### Arrow Calls
Use **->** to call a method on an object, passing the object as the first argument. This is equivalent to `((at obj 'method') obj args)`.

```
obj->method(args)
```

```
sequence->len();    // equivalent to ((at sequence 'len') sequence)
```

### Dot Calls
Use **.** to access properties or call methods on an object WITHOUT passing the object.

```
obj.method(args)
```

```
d.test(3, 4);       // equivalent to ((at d 'test') 3 4)
```

### Dot Access
Access nested object properties with **.**.

```
namespace.variables.shell
```

### Operators Table

| Category | Operators |
|:---------|:----------|
| Arithmetic | +, -, *, /, %, ^ |
| Comparison | ==, !=, <, >, <=, >= |
| Logical | &&, \|\|, ! |
| Type check | isa |
| Assignment | = |
| Arrow | -> |

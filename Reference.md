# Welcome to Riddle!
Riddle is a programming language that transpiles to Glosure.

## Syntax
Every statement must end with a **semicolon** — including bare literals, assignments, expressions, and `return`.

Code blocks are delimited by **braces**. Indentation matters only for readability.

Comments begin with **//**.

Conditions in **if**, **for**, **foreach** and **while** do NOT use parentheses around the condition — just write the expression directly.

## Identifiers & Naming

Identifiers can contain letters, digits, underscores and hyphens. They may end with `!` or `?`. Valid names:

```
gl-break-silence
empty?
effectful!
multiplayer?
my_var2
```

## Data Types & Literals

### Booleans
Boolean values are **true** and **false**.

| Operators | Description |
|:----------|:------------|
| `&&`      | Logical AND (short-circuit) |
| `\|\|`    | Logical OR (short-circuit) |
| `!`       | Logical NOT |
| `==`, `!=`| Equality |

### Numbers
Numbers are stored in full precision. Negative literals (e.g. `-145`) are supported directly.

| Operators | Description |
|:----------|:------------|
| `+`, `-`, `*`, `/` | Standard arithmetic |
| `%`          | Modulo |
| `^`          | Power |
| `==`, `!=`, `>`, `>=`, `<`, `<=` | Comparison |

### Strings
Strings are written in double quotes. Use `\"` to include a literal quote inside the string. Other escape sequences like `\n`, `\t` and `\\` are also supported.

```
print("Hello \"world\"!");
```

| Operators | Description |
|:----------|:------------|
| `[i]`       | Get character at index *i* |

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
| `[i]`       | Get/set element at index *i* |

### Dictionaries
Dictionaries map keys to values. Inline literals accept **any expression as a key**, separated from the value by `:`:

```
dict = {"name": "Riddle", 0: "zero", null: "nothing", true: "bool"};
```

Access or assign with any expression as the key via `[]`:

```
print(dict["name"]);
dict["version"] = 2;
dict[some_variable] = "dynamic";
```

| Operators | Description |
|:----------|:------------|
| `[k]`       | Get/set value with key *k* |

## Variables & Assignment

### Basic assignment
Use `=` to create a **new** variable binding:

```
a = 0;
b = "hello";
c = [1, 2, 3];
```

A second `=` with the same name creates a new binding in the current scope — it does NOT mutate the original.

### Reassignment
Use `<-` to reassign an **existing** variable in place:

```
a = 0;
a <- 1;    // a is now 1
```

### Compound assignment
Compound operators apply an arithmetic operation and assign the result in one step:

| Operator | Equivalent to |
|:---------|:--------------|
| `a += b` | `a <- a + b` |
| `a -= b` | `a <- a - b` |
| `a *= b` | `a <- a * b` |
| `a /= b` | `a <- a / b` |
| `a ^= b` | `a <- a ^ b` |
| `a %= b` | `a <- a % b` |

### Increment & Decrement
Prefix and postfix forms are both supported:

```
++a;     // increment a by 1 (value used after increment)
a++;     // increment a by 1 (value used before increment)
--a;     // decrement a by 1
a--;     // decrement a by 1
```

## Operators Table

| Category | Operators |
|:---------|:----------|
| Assignment | `=`, `<-`, `+=`, `-=`, `*=`, `/=`, `^=`, `%=` |
| Increment / Decrement | `++x`, `x++`, `--x`, `x--` |
| Arithmetic | `+`, `-`, `*`, `/`, `%`, `^` |
| Comparison | `==`, `!=`, `<`, `>`, `<=`, `>=` |
| Logical | `&&`, `\|\|`, `!` |
| Type check | `isa` |
| Arrow (method) | `->` |

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
} else if a < b {
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
    i <- i + 1;
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
for i = 0; i < 10; i <- i + 1 {
    print(i);
}
```

## Functions

Define a **host** function with `function` or a **Glosure** function with `defun`.

The difference is in how they are called at runtime:
- `function` creates a Glosure **defunction** — resolved via the host function lookup mechanism
- `defun` creates a Glosure **defun** — resolved via the Glosure function lookup mechanism

Both support default parameter values:

```
function add(a, b = 0) {
    return a + b;
}

defun multiply(a, b = 1) {
    return a * b;
}

print(add(3, 4));       // 7
print(multiply(5, 2));  // 10
```

### Namespaced methods
Methods on namespaced objects use dot notation in the definition:

```
function namespace.functions.Hello() {
    print("Hello!");
}
```

## Anonymous Functions (glosure/lambda)

Create an anonymous host function with **glosure** or anonymous Glosure function with **lambda**.

```
glosure (params) {
    body
}
```

```
apply = glosure (f, x) {
    return f(x);
};

somelist.apply(glosure (a1, a2 = 0) {
    print(a1);
});
```

## Method Calls

### Arrow Calls
Use `->` to call a method on an object, passing the object as the **first** argument.

```
obj->method(args)
```

```
sequence->len();    // equivalent to ((at sequence 'len') sequence)
```

### Dot Calls
Use `.` to call a method on an object **without** passing the object.

```
obj.method(args)
```

```
d.test(3, 4);       // equivalent to ((at d 'test') 3 4)
```

### Dot Access
Access nested object properties with `.`.

```
namespace.variables.shell
```

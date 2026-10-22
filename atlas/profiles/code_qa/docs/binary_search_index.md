# code_qa ref: binary_search_index

Q: How do you find the index of a target in a sorted list?

```python
def bsearch(xs, t):
    return xs.index(t) if t in xs else -1
```

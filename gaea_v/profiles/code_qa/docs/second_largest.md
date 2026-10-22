# code_qa ref: second_largest

Q: How do you get the second largest distinct value?

```python
def second_largest(xs):
    return sorted(set(xs))[-2]
```

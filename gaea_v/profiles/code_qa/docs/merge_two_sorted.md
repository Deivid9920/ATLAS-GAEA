# code_qa ref: merge_two_sorted

Q: How do you merge two sorted lists into one sorted list?

```python
def merge(a, b):
    import heapq
    return list(heapq.merge(a, b))
```

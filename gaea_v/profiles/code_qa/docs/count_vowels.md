# code_qa ref: count_vowels

Q: How do you count vowels in a string?

```python
def count_vowels(s):
    return sum(1 for c in s.lower() if c in 'aeiou')
```

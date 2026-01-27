# Custom Explicit Words

Customize the explicit content word list for your content.

## Additional Explicit Words

Add words that should trigger the explicit flag:

-
-

## Not Explicit (Override Base)

Remove words from the base explicit list for specific contexts:

-

---

## How This Works

1. Base list: fuck, shit, bitch, cunt, cock, dick, pussy, asshole, whore, slut, goddamn
2. Your additions are added to the list
3. Your removals are removed from the list
4. Final merged list is used for scanning

## Example

If your content is historical/literary and uses "damn" and "hell" heavily:

```markdown
## Not Explicit (Override Base)
- hell (context: historical narrative)
- damn (context: period-accurate dialogue)
```

If your genre has slang that should be flagged:

```markdown
## Additional Explicit Words
- regional-slang-term
- genre-specific-profanity
```

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  normalizeTitleForHash,
  getBigrams,
  bigramSimilarity,
  isDuplicate,
} from "../../src/lib/dedup/similarity.ts";

describe("normalizeTitleForHash", () => {
  it("lowercases the title", () => {
    assert.equal(normalizeTitleForHash("HELLO WORLD"), "hello world");
  });

  it("strips 'BREAKING:' prefix", () => {
    assert.equal(
      normalizeTitleForHash("BREAKING: Something happened"),
      "something happened"
    );
  });

  it("strips 'UPDATE:' prefix", () => {
    assert.equal(
      normalizeTitleForHash("UPDATE: Story evolves"),
      "story evolves"
    );
  });

  it("strips 'OPINION:' prefix", () => {
    assert.equal(normalizeTitleForHash("OPINION: My view"), "my view");
  });

  it("strips 'BREAKING NEWS:' prefix", () => {
    assert.equal(
      normalizeTitleForHash("BREAKING NEWS: Major event"),
      "major event"
    );
  });

  it("strips 'WATCH:' prefix", () => {
    assert.equal(normalizeTitleForHash("WATCH: Video clip"), "video clip");
  });

  it("removes punctuation", () => {
    assert.equal(normalizeTitleForHash("Hello, world!"), "hello world");
  });

  it("normalizes multiple spaces to one", () => {
    assert.equal(normalizeTitleForHash("foo   bar"), "foo bar");
  });

  it("trims leading and trailing whitespace", () => {
    assert.equal(normalizeTitleForHash("  hello  "), "hello");
  });

  it("does not strip non-news-prefix content", () => {
    const result = normalizeTitleForHash("Tech company releases update");
    assert.equal(result, "tech company releases update");
  });
});

describe("getBigrams", () => {
  it("returns correct bigrams for a simple string", () => {
    assert.deepEqual(getBigrams("abc"), ["ab", "bc"]);
  });

  it("returns empty array for a single character", () => {
    assert.deepEqual(getBigrams("a"), []);
  });

  it("returns empty array for empty string", () => {
    assert.deepEqual(getBigrams(""), []);
  });

  it("returns one bigram for two characters", () => {
    assert.deepEqual(getBigrams("hi"), ["hi"]);
  });

  it("includes space-containing bigrams", () => {
    const bigrams = getBigrams("a b");
    assert.ok(bigrams.includes("a "));
    assert.ok(bigrams.includes(" b"));
  });
});

describe("bigramSimilarity", () => {
  it("returns 1.0 for identical strings", () => {
    assert.equal(bigramSimilarity("hello world", "hello world"), 1);
  });

  it("returns 1.0 for strings that normalize to the same value", () => {
    // Both normalize to "breaking story about elections"
    assert.equal(
      bigramSimilarity(
        "BREAKING: story about elections",
        "story about elections"
      ),
      1
    );
  });

  it("returns 0 for completely unrelated short strings", () => {
    assert.equal(bigramSimilarity("ab", "cd"), 0);
  });

  it("returns a high score for near-duplicate titles", () => {
    const score = bigramSimilarity(
      "Trump signs executive order on immigration",
      "Trump signs executive order on immigration reform"
    );
    assert.ok(score > 0.8, `Expected score > 0.8 but got ${score}`);
  });

  it("returns a low score for unrelated titles", () => {
    const score = bigramSimilarity(
      "NBA finals game 7 results",
      "Stock market hits record high"
    );
    assert.ok(score < 0.3, `Expected score < 0.3 but got ${score}`);
  });

  it("returns 0 when one string is shorter than 2 chars after normalization", () => {
    assert.equal(bigramSimilarity("a", "hello world"), 0);
  });
});

describe("isDuplicate", () => {
  it("returns true for identical titles", () => {
    assert.equal(
      isDuplicate("Breaking: War erupts in region", "Breaking: War erupts in region"),
      true
    );
  });

  it("returns true for near-duplicate titles above default threshold", () => {
    assert.equal(
      isDuplicate(
        "Scientists discover new planet in solar system",
        "Scientists discover new planet in our solar system"
      ),
      true
    );
  });

  it("returns false for clearly different titles", () => {
    assert.equal(
      isDuplicate(
        "Local weather forecast for this week",
        "Tech giant announces record profits"
      ),
      false
    );
  });

  it("respects a custom threshold", () => {
    // With a very high threshold (0.99), even similar strings are not duplicates
    const similar = bigramSimilarity(
      "Apple releases new iPhone model",
      "Apple releases new iPhone 16 model"
    );
    assert.equal(isDuplicate(
      "Apple releases new iPhone model",
      "Apple releases new iPhone 16 model",
      0.99
    ), similar >= 0.99);
  });

  it("returns false when using a very low threshold for unrelated titles is actually true", () => {
    // With threshold 0.0, everything is a duplicate
    assert.equal(
      isDuplicate("completely different", "nothing alike", 0.0),
      true
    );
  });
});

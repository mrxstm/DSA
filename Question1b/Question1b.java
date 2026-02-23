import java.util.*;

public class Question1b {

    // Main function to generate all keyword sentences
    public static List<String> segmentKeywords(String userQuery, Set<String> dictionary) {
        // Memoization map: substring -> list of sentences
        Map<String, List<String>> memo = new HashMap<>();
        return backtrack(userQuery, dictionary, memo);
    }

    // Backtracking function with memoization
    private static List<String> backtrack(String s, Set<String> dictionary, Map<String, List<String>> memo) {
        // If result already computed, return from memo
        if (memo.containsKey(s)) {
            return memo.get(s);
        }

        List<String> result = new ArrayList<>();

        // Base case: empty string
        if (s.isEmpty()) {
            result.add(""); // Represents a valid path completion
            return result;
        }

        // Try every possible prefix
        for (int i = 1; i <= s.length(); i++) {
            String prefix = s.substring(0, i);

            // Check if prefix is a valid keyword
            if (dictionary.contains(prefix)) {
                String suffix = s.substring(i);

                // Recursively solve the suffix
                List<String> suffixSentences = backtrack(suffix, dictionary, memo);

                // Combine prefix with all valid suffix sentences
                for (String sentence : suffixSentences) {
                    if (sentence.isEmpty()) {
                        result.add(prefix);
                    } else {
                        result.add(prefix + " " + sentence);
                    }
                }
            }
        }

        // Store computed result in memo
        memo.put(s, result);
        return result;
    }

    // Driver / testing
    public static void main(String[] args) {
        String userQuery = "nepaltrekkingguide";
        Set<String> dictionary = new HashSet<>(Arrays.asList("nepal", "trekking", "guide", "nepaltrekking"));

        List<String> segmentedSentences = segmentKeywords(userQuery, dictionary);

        System.out.println("All possible segmented sentences:");
        for (String sentence : segmentedSentences) {
            System.out.println(sentence);
        }
    }
}
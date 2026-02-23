class TreeNode {
    int val;
    TreeNode left;
    TreeNode right;

    TreeNode(int val) {
        this.val = val;
        this.left = null;
        this.right = null;
    }
}

public class Question2 {

    // Stores the maximum net power found
    static int maxPower;

    // Main function
    public static int maxPathSum(TreeNode root) {
        maxPower = Integer.MIN_VALUE;
        dfs(root);
        return maxPower;
    }

    // DFS using post-order traversal
    static int dfs(TreeNode node) {
        if (node == null)
            return 0;

        // Get maximum contribution from left and right
        int left = Math.max(0, dfs(node.left));
        int right = Math.max(0, dfs(node.right));

        // Path passing through current node
        int currentPath = node.val + left + right;

        // Update global maximum
        maxPower = Math.max(maxPower, currentPath);

        // Return best single path to parent
        return node.val + Math.max(left, right);
    }

    // Example test
    public static void main(String[] args) {

        /*
                -10
               /   \
              9     20
                   /  \
                 15    7
        */

        TreeNode root = new TreeNode(-10);
        root.left = new TreeNode(9);
        root.right = new TreeNode(20);
        root.right.left = new TreeNode(15);
        root.right.right = new TreeNode(7);

        System.out.println("Maximum Net Power Generation: " + maxPathSum(root));
    }
}

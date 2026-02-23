public class Question3 {

    public static int maxProfit(int[] daily_prices, int maxTrades) {

        int n = daily_prices.length;

        /*
         * DP table definition:
         * dp[day][transactions][holding]
         */

        int[][][] dp = new int[n + 1][maxTrades + 1][2];

        for (int day = n - 1; day >= 0; day--) {
            for (int t = 0; t <= maxTrades; t++) {

                /*
                 * CASE 1: Not holding any commodity (holding = 0)
                 */
                if (t < maxTrades) {
                    dp[day][t][0] = Math.max(
                        -daily_prices[day] + dp[day + 1][t][1], // Buy
                        dp[day + 1][t][0]                       // Skip
                    );
                } else {
                    // No transactions left → cannot buy
                    dp[day][t][0] = dp[day + 1][t][0];
                }

                /*
                 * CASE 2: Holding commodity (holding = 1)
                 */
                if (t < maxTrades) {
                    dp[day][t][1] = Math.max(
                        daily_prices[day] + dp[day + 1][t + 1][0], // Sell
                        dp[day + 1][t][1]                          // Hold
                    );
                } else {
                    // No transactions left → cannot sell
                    dp[day][t][1] = dp[day + 1][t][1];
                }
            }
        }

        /*
         * Starting point:
         * Day 0, 0 transactions used, not holding any commodity
         */
        return dp[0][0][0];
    }

    public static void main(String[] args) {

        int[] daily_prices = {2000, 4000, 1000};
        int max_trades = 2;

        int result = maxProfit(daily_prices, max_trades);

        System.out.println("Maximum Profit = " + result + " NPR");
    }
}



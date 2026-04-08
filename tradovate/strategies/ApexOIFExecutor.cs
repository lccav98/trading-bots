// Apex OIF Executor - Simple strategy to execute OIF orders
// No indicators, just executes orders sent via ATI

namespace NinjaTrader.Strategy
{
    public class ApexOIFExecutor : Strategy
    {
        protected override void OnBarUpdate()
        {
            // No trading logic - orders come via OIF
        }
        
        protected override void OnOrderSubmit(Order order)
        {
            Print("OIF Order submitted: " + order.Action + " " + order.Quantity + " " + order.Instrument);
        }
        
        protected override void OnExecution(Execution execution)
        {
            Print("OIF Execution: " + execution.Order.Action + " " + execution.Order.Quantity + " @ " + execution.Order.Price);
        }
    }
}
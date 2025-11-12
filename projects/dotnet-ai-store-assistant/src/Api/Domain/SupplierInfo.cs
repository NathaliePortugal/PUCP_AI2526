namespace Api.Domain
{
    public class SupplierInfo
    {
        public string Name { get; set; } = default!;
        public string Url { get; set; } = default!;
        public bool InStock { get; set; } = default!;
        public decimal Price { get; set; } = default!;
        public DateTime LastUpdated { get; set; } = DateTime.UtcNow;
        public SupplierInfo(string name, string url, bool stock, decimal price)
        {
            Name = name;
            Url = url;
            InStock = stock;
            Price = price;
        }
    }
}
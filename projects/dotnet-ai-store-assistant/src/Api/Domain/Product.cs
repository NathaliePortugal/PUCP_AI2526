namespace Api.Domain;

public class Product
{
    public string Id { get; set; } = default!;
    public string Sku { get; set; } = default!;
    public string Title { get; set; } = default!;
    public string Description { get; set; } = default!;
    public string ImageUrl { get; set; } = default!;
    public List<SupplierInfo> Suppliers { get; set; } = new();
    public List<string> Tags { get; set; } = new();
    public DateTime IndexedAt { get; set; } = DateTime.UtcNow;
}


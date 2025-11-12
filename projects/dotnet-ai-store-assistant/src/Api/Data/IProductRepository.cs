using Api.Domain;

namespace Api.Data;
public interface IProductRepository
{
    Task<Product?> GetBySkuAsync(string sku, CancellationToken ct);
    Task<IReadOnlyList<Product>> SearchAsync(string query, int limit, CancellationToken ct);
    Task UpsertManyAsync(IEnumerable<Product> products, CancellationToken ct);
}

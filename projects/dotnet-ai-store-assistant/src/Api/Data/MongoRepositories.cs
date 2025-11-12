using Api.Domain;
using MongoDB.Driver;

namespace Api.Data;

public class MongoProductRepository(IMongoDatabase db) : IProductRepository
{
    private readonly IMongoCollection<Product> _col = db.GetCollection<Product>("products");

    public async Task<Product?> GetBySkuAsync(string sku, CancellationToken ct) =>
        await _col.Find(p => p.Sku == sku).FirstOrDefaultAsync(ct);

    public async Task<IReadOnlyList<Product>> SearchAsync(string query, int limit, CancellationToken ct)
    {
        var filter = Builders<Product>.Filter.Text(query) |
                     Builders<Product>.Filter.Regex(p => p.Title, query);
        return await _col.Find(filter).Limit(limit).ToListAsync(ct);
    }

    public async Task UpsertManyAsync(IEnumerable<Product> products, CancellationToken ct)
    {
        var writes = products.Select(p =>
            new ReplaceOneModel<Product>(Builders<Product>.Filter.Eq(x => x.Id, p.Id), p) { IsUpsert = true });
        await _col.BulkWriteAsync(writes, cancellationToken: ct);
    }
}

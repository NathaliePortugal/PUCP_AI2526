using Api.Data;
using Api.Domain;
using Api.Embeddings;

namespace Api.Services;

public class RecommendationService(IProductRepository repo, IEmbeddingProvider embed)
{
    public async Task<IReadOnlyList<Product>> SimilarAsync(string term, int k, CancellationToken ct)
    {
        var all = await repo.SearchAsync(term, 100, ct);
        var q = embed.Embed(term);
        return all
            .Select(p => (p, s: IEmbeddingProvider.Cosine(q, embed.Embed($"{p.Title} {p.Description}"))))
            .OrderByDescending(t => t.s)
            .Take(k)
            .Select(t => t.p)
            .ToList();
    }
}

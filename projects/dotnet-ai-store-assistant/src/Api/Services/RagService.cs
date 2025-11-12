using Api.Data;
using Api.Domain;
using Api.Embeddings;
using Api.Llm;

namespace Api.Services;

public class RagService
{
    private readonly IProductRepository _repo;
    private readonly IEmbeddingProvider _embed;
    private readonly ILlmClient _llm;
    private readonly PromptTemplateService _templates;
    private readonly int _topK;

    public RagService(IProductRepository repo, IEmbeddingProvider embed, ILlmClient llm, IConfiguration cfg, PromptTemplateService templates)
    {
        _repo = repo;
        _embed = embed;
        _llm = llm;
        _templates = templates;
        _topK = cfg.GetValue("Rag:TopK", 5);
    }
    public async Task<string> AskAsync(string userPrompt, UserProfile user, string mode = "friendly", CancellationToken ct = default)
    {
        var candidates = await _repo.SearchAsync(userPrompt, 50, ct) ?? Array.Empty<Product>();
        var qVec = _embed.Embed(userPrompt);

        var scored = candidates
            .Select(p => new {
                Product = p,
                Score = IEmbeddingProvider.Cosine(qVec, _embed.Embed($"{p.Title} {p.Description}"))
            })
            .OrderByDescending(x => x.Score)
            .Take(_topK)
            .ToList();

        var context = string.Join("\n---\n", scored.Select(s =>
            $"{s.Product.Title} | {s.Score:F2}\n{s.Product.Description}"));

        var (systemPrompt, userPromptText) = _templates.BuildPrompt(user, userPrompt, mode);

        return await _llm.GenerateAsync(systemPrompt, userPromptText, context, ct);
    }
}

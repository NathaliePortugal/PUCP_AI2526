namespace Api.Llm;
public interface ILlmClient
{
    Task<string> GenerateAsync(string systemPrompt, string userPrompt, string context, CancellationToken ct);
}

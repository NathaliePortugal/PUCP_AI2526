namespace Api.Llm;

public class FakeLlmClient : ILlmClient
{
    public Task<string> GenerateAsync(string systemPrompt, string userPrompt, string context, CancellationToken ct)
    {
        // Respuesta determinística, “parecida” a un LLM, útil para tests/evaluación
        var summary = string.Join(' ', context.Split(' ').Take(60));
        var answer = $"[Sim-LLM] Q: {userPrompt}\n\nContexto:\n{summary}\n\nRespuesta: Según el inventario, te propongo 3 opciones relevantes.";
        return Task.FromResult(answer);
    }
}

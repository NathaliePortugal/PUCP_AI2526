using Api.Domain;
using Api.Services;

namespace Api.Endpoints;

public static class ChatEndpoints
{
    public static IEndpointRouteBuilder MapChatEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapPost("/api/chat", async (RagService rag, UserProfile user, string prompt, CancellationToken ct) =>
        {
            var answer = await rag.AskAsync(prompt, user, ct);
            return Results.Ok(new { answer });
        });

        return app;
    }
}

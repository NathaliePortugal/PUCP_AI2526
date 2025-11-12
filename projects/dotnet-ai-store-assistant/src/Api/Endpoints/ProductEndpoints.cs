using Api.Data;
using Api.Services;

namespace Api.Endpoints;

public static class ProductEndpoints
{
    public static IEndpointRouteBuilder MapProductEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/products");

        group.MapGet("/search", async (IProductRepository repo, string q, int limit, CancellationToken ct)
            => Results.Ok(await repo.SearchAsync(q, limit <= 0 ? 10 : limit, ct)));

        group.MapPost("/backfill", async (QueuePublisher qp, string sku, string missingVendor, CancellationToken ct) =>
        {
            await qp.PublishBackfillAsync(new { kind = "BackfillRequest", sku, missingVendor, ts = DateTime.UtcNow }, ct);
            return Results.Accepted();
        });

        return app;
    }
}

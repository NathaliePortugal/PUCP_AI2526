using Api;
using Api.Data;
using Api.Domain;
using Api.Embeddings;
using Api.Llm;
using Api.Services;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Microsoft.VisualStudio.TestPlatform.TestHost;
using Moq;

public class CustomWebApplicationFactory : WebApplicationFactory<Program>
{
    public Mock<IProductRepository> ProductRepoMock { get; } = new();

    protected override void ConfigureWebHost(Microsoft.AspNetCore.Hosting.IWebHostBuilder builder)
    {
        builder.ConfigureServices(services =>
        {
            // Removemos los servicios reales registrados en Program.cs
            services.RemoveAll<IProductRepository>();
            services.RemoveAll<IEmbeddingProvider>();
            services.RemoveAll<ILlmClient>();

            // Registramos los mocks o versiones fakes
            services.AddSingleton<IProductRepository>(_ => ProductRepoMock.Object);
            services.AddSingleton<IEmbeddingProvider>(_ => new HashingEmbeddingProvider(64));
            services.AddSingleton<ILlmClient>(_ => new FakeLlmClient());
        });
    }
}

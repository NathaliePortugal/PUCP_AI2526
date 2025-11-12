using Api.Controllers;
using Api.Data;
using Api.Domain;
using Api.Embeddings;
using Api.Services;
using FluentAssertions;
using Moq;
using Xunit;

public class RecommendationsControllerTests
{
    [Fact]
    public async Task Similar_ReturnsListOfRecommendations()
    {
        // Arrange
        var repoMock = new Mock<IProductRepository>();
        repoMock.Setup(r => r.SearchAsync(It.IsAny<string>(), It.IsAny<int>(), It.IsAny<CancellationToken>()))
                .ReturnsAsync(new List<Product>
                {
                    new() { Sku="TES-1516", Title="Cargador Tesla 1516", Description="Carga rápida" },
                    new() { Sku="EV-FAST",  Title="Cargador EV 22kW",   Description="Compatible Tesla" }
                });

        var embed = new HashingEmbeddingProvider(64);
        var recService = new RecommendationService(repoMock.Object, embed);
        var controller = new RecommendationsController(recService);

        // Act
        var result = await controller.Similar("Tesla", 5, default)
                      as Microsoft.AspNetCore.Mvc.OkObjectResult;
        var data = result?.Value as IEnumerable<Product>;

        // Assert
        result.Should().NotBeNull();
        data.Should().NotBeNull();
        data!.Should().NotBeEmpty();
        data!.First().Title.Should().Contain("Cargador");
    }
}

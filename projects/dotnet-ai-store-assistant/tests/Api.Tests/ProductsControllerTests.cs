using Api.Domain;
using Api.Data;
using Api.Services;
using FluentAssertions;
using Moq;
using Xunit;

public class ProductsControllerTests
{
    private readonly Mock<IProductRepository> _repoMock = new();

    [Fact]
    public async Task Search_ReturnsProductsFromRepository()
    {
        // Arrange
        var fakeProducts = new List<Product>
        {
            new() { Sku = "TES-1516", Title = "Cargador Tesla", Description = "Carga rápida" },
            new() { Sku = "EV-FAST", Title = "Cargador EV", Description = "22kW" }
        };
        _repoMock.Setup(r => r.SearchAsync("tesla", It.IsAny<int>(), It.IsAny<CancellationToken>()))
                 .ReturnsAsync(fakeProducts);

        var controller = new Api.Controllers.ProductsController(_repoMock.Object);

        // Act
        var result = await controller.Search("tesla", 10, default) as Microsoft.AspNetCore.Mvc.OkObjectResult;
        var data = result?.Value as IEnumerable<Product>;

        // Assert
        result.Should().NotBeNull();
        data.Should().HaveCount(2);
        data!.First().Sku.Should().Be("TES-1516");
    }
}

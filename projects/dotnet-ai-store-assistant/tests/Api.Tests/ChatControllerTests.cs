// tests/Api.Tests/ChatControllerTests.cs
using System.Net.Http.Json;
using Api.Domain;
using FluentAssertions;
using Moq;
using Xunit;

public class ChatControllerTests : IClassFixture<CustomWebApplicationFactory>
{
    private readonly CustomWebApplicationFactory _factory;
    private readonly HttpClient _client;

    public ChatControllerTests(CustomWebApplicationFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();
    }

    [Fact]
    public async Task PostChat_ShouldReturnSimulatedLlmAnswer()
    {
        // Arrange
        _factory.ProductRepoMock
        .Setup(r => r.SearchAsync(It.IsAny<string>(), It.IsAny<int>(), It.IsAny<CancellationToken>()))
        .ReturnsAsync(new List<Product>
        {
            new()
            {
                Id = "1", Sku = "TES-1516",
                Title = "Cargador Automático Tesla 1516",
                Description = "Carga rápida",
                Tags = new() { "cargador","tesla","ev" },
                Suppliers = new()
                {
                    new("Grainger","https://x", false, 1200m),
                    new("Lowes","https://y", true, 1150m)
                }
            }
        });

        var fakeUser = new UserProfile { Id = "u1", Email = "nathy@example.com" };
        var payload = new ChatRequest(fakeUser, "Cargador Tesla"); 

        // Act
        var response = await _client.PostAsJsonAsync("/api/chat", payload);
        var json = await response.Content.ReadFromJsonAsync<Dictionary<string, string>>();

        // Assert
        response.IsSuccessStatusCode.Should().BeTrue();
        json.Should().ContainKey("answer");
        json!["answer"].Should().Contain("Sim-LLM");
    }
}

namespace Api.Domain;

public class UserProfile
{
    public string Id { get; set; } = default!;
    public string Email { get; set; } = default!;
    public List<string> PreferredVendors { get; set; } = new();
    public List<string> BlockedVendors { get; set; } = new();
    public List<string> FavoriteTags { get; set; } = new();
}

package nl.hackyourfuture.project.backend.user.dto;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record UserRequest(
        @NotBlank(message = "Please provide an email")
        @Size(min=3,max=100)
        @Email
        String email
) {}
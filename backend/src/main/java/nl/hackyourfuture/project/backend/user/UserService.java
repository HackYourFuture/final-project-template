package nl.hackyourfuture.project.backend.user;

import lombok.RequiredArgsConstructor;
import nl.hackyourfuture.project.backend.user.dto.*;
import org.springframework.stereotype.Service;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class UserService {
    private final UserRepository userRepository;

    public List<UserResponse> getAllUsers() {
        return userRepository.getAllUsers().stream().map(UserResponse::from).toList();
    }

    public UserResponse createUser(UserRequest request) {
        var newUser = User.builder()
                .id(UUID.randomUUID())
                .email(request.email())
                .build();
        var created = userRepository.createUser(newUser);
        return UserResponse.from(created);
    }

    public UserResponse updateUser(UUID id, UserRequest request) {
        var updatedUser = User.builder()
                .id(id)
                .email(request.email())
                .build();
        var updated = userRepository.updateUser(updatedUser);
        return UserResponse.from(updated);
    }
}

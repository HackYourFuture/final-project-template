package nl.hackyourfuture.project.backend.user;

import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import java.util.List;
import java.util.UUID;

@Repository
@RequiredArgsConstructor
public class UserRepository {
    private final JdbcClient jdbcClient;

    public static final RowMapper<User> USER_ROW_MAPPER = (rs, _) -> User.builder()
            .id(rs.getObject("id", UUID.class))
            .email(rs.getString("email"))
            .build();

    public List<User> getAllUsers() {
        return jdbcClient
                .sql("SELECT id, email FROM users")
                .query(USER_ROW_MAPPER)
                .list();
    }

    public User createUser(User user) {
        jdbcClient
                .sql("INSERT INTO users (id, email) " +
                        "VALUES (:id, :email)")
                .param("id", user.getId())
                .param("email", user.getEmail())
                .update();
        return user;
    }

    public User updateUser(User user) {
        jdbcClient.sql("""
                        UPDATE users
                        SET email=:email
                        WHERE id=:id
                        """)
                .param("id", user.getId())
                .param("email", user.getEmail())
                .update();
        return user;
    }
}

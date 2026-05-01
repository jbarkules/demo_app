class AddProfileFieldsToUsers < ActiveRecord::Migration[8.0]
  def change
    add_column :users, :role, :integer
    add_column :users, :display_name, :string
    add_column :users, :company_name, :string
    add_column :users, :trade, :string
    add_column :users, :location, :string
    add_column :users, :bio, :text
  end
end

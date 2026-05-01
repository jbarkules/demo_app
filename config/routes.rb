Rails.application.routes.draw do
  resource  :session
  resources :passwords, param: :token
  resources :registrations, only: [ :new, :create ]

  resources :users, only: [ :index, :show ] do
    resources :reviews, only: [ :new, :create ], shallow: true
  end
  resources :reviews, only: [ :index, :show, :destroy ]

  get "up" => "rails/health#show", as: :rails_health_check

  root "users#index"
end
